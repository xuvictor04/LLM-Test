# Phase 11 — the context export (and the STATE.md reliability discovery)

The user asked to export the full context to a new chat as a standalone document (`PROJECT_CONTEXT_EXPORT.md`, plus
`START_HERE.md` / `GLOSSARY.md` / `COMMANDS.md`). Preparing it, a direct check of disk found that **`STATE.md` had
silently stopped being written after roughly its first quarter (~T4)** — later turns narrated edits to it that never
landed. The CODE files were all current and verified; only the ledger had drifted. Disclosed rather than hidden.

**Guidance from that export:** treat `STATE.md` as unreliable past its own "T4" and prefer the export + the code + the
measured numbers; and fix the ledger's reliability (or replace its protocol with something self-verifying).

**What this repo did with it (repo turn R4):** rebuilt `STATE.md` from the export (real history restored as phases,
stale §7 replaced, self-verify step added to the protocol), and folded the export into this `handoff/` folder as atomic
files. See `../migrations/` for the repo-side hand-off log.
</content>
