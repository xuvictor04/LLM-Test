# Verify ledger/file edits actually landed before claiming success

`STATE.md` — the ledger the protocol requires updated every turn — once **silently stopped being written to disk for
~30 turns** while later turns kept narrating edits to it as if they had succeeded. That is the single root cause of the
project's worst drift. Rule: after any edit to a tracked file (especially `STATE.md`), re-read or grep the changed lines
and confirm they are present before reporting the change done. An unverified write is not a done write.

**Source:** context export §14; `../../STATE.md` protocol #2.
