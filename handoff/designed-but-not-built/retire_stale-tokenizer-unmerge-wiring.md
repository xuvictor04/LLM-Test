# retire_stale() tokenizer un-merge wiring — BUILT in isolation, not wired

**What:** `DynamicTokenizer.retire_stale()` can un-merge tokens that stop being used (shrink the vocabulary). Built and
tested in isolation.
**Status:** NOT connected to the live training loop — so the online vocabulary currently only GROWS, never shrinks.
Wiring it in is the remaining step.
**Source:** context export §5, §11; `tokenizer.py`.
