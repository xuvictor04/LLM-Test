# 2026-07-21 (b) — Folded the prior-context export in; rebuilt STATE.md

**Context:** the user brought back four documents the *prior chat* produced (`PROJECT_CONTEXT_EXPORT.md`, `START_HERE.md`,
`GLOSSARY.md`, `COMMANDS.md`) plus that chat's answers to the open questions. This turn integrated all of it.

## The big correction
My earlier migration note claimed the T5–T32 history was "unrecoverable." **That was wrong** — the prior context
reconstructed the entire history (Phases 0–11) from the still-visible conversation; it is now in `../history/`. Root
cause of the drift: **`STATE.md` silently stopped saving to disk after ~T4** in the original environment while later
turns narrated edits to it. (Saving is verified working in this repo.)

## What this turn did (user chose: keep granular atomic files + fold in; rebuild STATE.md + self-verify)
- **Rebuilt `../../STATE.md`** from the export: restored history as Phases (§6), replaced the stale §7 with the
  authoritative measured results, added a self-verify step to the protocol, folded new decisions into §2, refreshed §3/§4/§5.
- **Folded the export into atomic files:** `../GLOSSARY.md`, `../COMMANDS.md`, `../history/` (12 phases),
  `../designed-but-not-built/` (5), new `../decisions/` (prediction-level ensembling, byte-stream encoder, society-not-mixture,
  internal-only grounding, no-pretrained-base goal, release-not-cascade deletion, GRU default, fab_logits invariant),
  new `../process/` (name-blockers, sandbox-constraints, verify-edits-land), `../data-and-scaling-status.md`, `../recommended-next-steps.md`.
- **Updated `../open-questions/`:** Q0 + Q3 now carry the prior-context recommendations; management ablation (old Q1) is
  RESOLVED → moved to `../decisions/`; added Q-regime and Q-compute.
- Did NOT add the 4 source docs whole (user chose granular-fold-in over adding-them-whole). `PROJECT_CONTEXT_EXPORT.md`'s
  content is distributed across the files above rather than kept as one file.

## State of play now
- Latest ACTUAL GPU numbers: Garry (redundancy) 1.967 / −0.0009; modularity 2.002 / +0.127. Everything after Phase 10
  (grounding, `BATCH_W`, `fetch_big.py`) is built + CPU-tested, NOT GPU-run.
- Four decisions still need the USER: expert-evolution (Q0), B direction (Q3), regime (Q-regime), compute budget (Q-compute).
  Recommendations are on file for Q0 (Darwinian fitness) and Q3 (cut B); none for the two product/scale forks.

## For the next chat
`STATE.md` is trustworthy again and is the single source of truth. Verify your own edits land (protocol #2). The prior
context's original 4 docs live in the user's upload history, not the repo — their content is here, atomized.
</content>
