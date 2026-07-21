# Routing = embedding + similarity — the source of reuse and transfer [USER direction]

**Answers the previously-open question "what makes a sub-skill reusable across tasks?"** Reusability comes from the
ROUTER, DISCOVERY, and SIMILARITY.

**Router-as-embedder (USER):** the router may act like an EMBEDDER — take an input (AND its SOURCE), apply a MODIFICATION,
then EMBED it to determine which expert is most SIMILAR (or route by learned RECOGNITION). Because routing is by
similarity in an embedding space, a NEW/unknown input that lands near a known sub-skill routes to it — **transfer to
prior-unknown parts falls out for free.**

**Why this is the reuse mechanism:** a sub-skill is reused whenever a new sub-task embeds near it. So sub-skills
generalize across tasks IF the embedding makes functionally-similar sub-tasks land together — that is the whole game.

**The "modification" step (hypothesis):** the modification applied before embedding is plausibly where surface content is
ABSTRACTED AWAY so that FUNCTIONAL similarity (same procedure needed) emerges instead of mere content similarity.

**The deep tension — MECHANISM VALIDATED (CPU, `keystone_probe.py`, 2026-07-21):** the current signature encoder learns
CONTENT similarity (InfoNCE); sub-skill reuse needs FUNCTIONAL similarity (different content, SAME procedure — "sort
numbers" vs "sort words"). Probe result: an embedding trained as a REUSABLE code that must TRANSFER across content
(z from one input→output pair must transform a NEW input under the same op) organizes by FUNCTION — op-purity 0.80 vs
0.50 surface (chance 0.20). Naive same-input coding gave only 0.61 (z cheated with content). **So the "modification
before embedding" step is concretely CROSS-CONTENT TRANSFER training.** Functional similarity is learnable — reuse/transfer
is buildable. (Toy synthetic; real integration into the router is future.)

**Source:** user, session 2026-07-21.
</content>
