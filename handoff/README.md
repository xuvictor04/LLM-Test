# handoff/ — START HERE (assume you have ZERO prior context)

You are (most likely) a fresh chat with no memory of earlier sessions. This project **migrates chats when
context can no longer be compressed**, and *this folder is how context is exchanged between chats.* Read it
and you can continue without the prior conversation.

## Read in this order
1. **This file.**
2. **`NORTH_STAR.md`** — what the project is ultimately FOR (the goal + the sacred growability invariant). Read this early.
3. `../README.md` — what the project is (the pitch).
4. `migrations/` — newest dated file = the latest state of play.
4. `../STATE.md` — the LIVE ledger and single source of truth: §1 what it is + the two regimes, §2 decisions you
   must honor, §4 the four OPEN decisions, §5 config, §6 phase history, §7 measured numbers.
5. `history/` — the full narrative as atomic per-phase files (how every current decision got made).
6. `GLOSSARY.md` — the overloaded terms (domain / expert / node / fabric / society / regimes). Read before touching code.
7. `COMMANDS.md` — every run command, each flag verified present in the code.
8. `designed-but-not-built/` — specified future work, one item per file.
9. `../docs/FILES.md` (file-by-file map) and `../docs/HANDOFF.md` (snapshot + reconciliation ledger).
10. `../garry/GARRY.md` — the frozen milestone with exact config + numbers.

## The four decisions that need YOU before more architecture work (`open-questions/`, full text in `STATE.md §4`)
1. **Expert evolution** — fitness is pure occupancy (`fit = use/age`), never approved. Rec on file: Darwinian per-loss fitness.
2. **B (wrong-detection)** — ~1% precision every realistic run. Rec on file: cut it, rely on A (editing) which already works.
3. **Redundancy vs modularity** — the society runs either free-to-delete-but-interchangeable, or specialized-but-costs-something. Both measured. Pick one or keep both.
4. **Compute budget** — data + throughput blockers resolved; NOTHING run at the new scale yet. GPT-2's budget is weeks of H100 time, not hours.

## How this folder is organized
**One idea per file. The filename IS the summary — `ls` a subfolder and you have the map.**
`process/` (how we work) · `decisions/` (settled `[USER]` calls) · `open-questions/` (needs a USER decision) ·
`design-directions/` (vision the user has set, mechanism still open) · `designed-but-not-built/` (specified, unbuilt) ·
`history/` (per-phase narrative) · `migrations/` (dated hand-offs).

## Relationship to STATE.md (avoid drift — this is the lesson that created this folder)
`STATE.md` is the single LIVE source of truth. Everything here is short and points back to it. **The reason §6/§7 of
STATE.md once went stale for ~30 turns is that a second file held a copy and the two drifted** — so more copies of the
same information is the risk, not the safeguard. Update `STATE.md` first (and verify the edit landed), then reflect headlines here.

## How to hand off when THIS chat is retired
Add a new dated file to `migrations/` (e.g. `2026-08-01-<what-happened>.md`): what changed, what is now true, what is
still open, what the next chat must NOT repeat. Descriptive filename. Assume the reader knows nothing.

## The project in one paragraph
An autonomous continual-learning system driven by one unlabeled stream: it self-assembles domains, grows a society of
independent experts (the Fabric), writes surprise-gated memory tagged by provenance, detects wrong info (B, detect-only),
and edits/unlearns by provenance (A). Headline, reproducible result: **deleting a whole expert's weights costs less
collateral than deleting a handful of memory rows, and far less than gradient-ascent unlearning** — independence makes
removal clean. The stated end goal is a **full novel model trained from scratch that can hold a conversation** — a long
way from the current numbers. **This chat environment has no GPU**; the user runs the real suite on their own H100 and pastes results back.
</content>
