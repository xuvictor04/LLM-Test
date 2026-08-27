# Experts can be tool calls / scripts — self-authored on repetition, like tokens [USER direction]

**Idea:** an "expert" need not be only a neural adapter. Some experts can **terminate in a tool call or a pre-established
SCRIPT** — a discrete, deterministic procedure. Crucially, the system can **create these itself when a pattern recurs
often enough** — exactly like the tokenizer mints a token on repetition. A frequently-repeated procedure crystallizes
into a reusable tool-expert.

**Why it fits the whole design:**
- It's the SAME crystallize-on-repetition primitive already used for tokens (byte patterns) — now applied to PROCEDURES
  (see `the-unifying-primitive-subtokenization-embed-and-match-at-every-layer.md`).
- It serves the "much smaller than conventional" north star: offloading a stable, repeated computation to a script is far
  cheaper than carrying it in weights.
- It's the editability thesis for free: a script is as removable/updatable as a database row.

**Open:** how a recurring NEURAL pattern is distilled/compiled into a script; how tool-experts and neural experts share
ONE routing/embedding space; how a self-authored tool-expert is validated before it's trusted; safety of self-authored scripts.
**Source:** user, session 2026-07-21.
</content>
