# Phase 1 — cleanup, the ledger, and the expanding tokenizer

Triple-checked the active API; moved 57 dormant files to `legacy/` (not deleted). On "add back what you can," salvaged an
adaptive write-gate (self-calibrating, since the surprise scale drifts as the model trains) but declined to force in a
tokenizer unasked.

Then, asked for tokenizer integration, Claude first used the STATIC `ByteBPE` — the user immediately corrected:
**"No, I want the prior expanding tokenizer"** (the `DynamicTokenizer` that grows online via mint-on-repetition). Swapped
in. This mattered: an online-growing vocab is a fundamentally different, more failure-prone mechanism than a fixed BPE —
most of the project's hardest bugs trace to things that only churn under a *growing* vocabulary.

The user's ledger-defining instruction: **"We keep defaulting to your own defaults... Produce and keep constantly updated
a document."** → `STATE.md` + its protocol was created. (It later went stale for ~30 turns — see Phase 11 / `../process/verify-ledger-edits-actually-landed...`.)
</content>
