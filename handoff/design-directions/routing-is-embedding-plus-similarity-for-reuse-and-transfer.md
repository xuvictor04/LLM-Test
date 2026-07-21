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

**The deep tension (OPEN, make-or-break):** the current signature encoder learns CONTENT similarity (InfoNCE:
nearby-in-stream = similar). Sub-skill reuse needs FUNCTIONAL similarity — two inputs of different content that need the
SAME procedure ("sort numbers" vs "sort words"). Whether the router's space can capture FUNCTION, not just content,
decides whether reuse/transfer actually works. This is the crux to solve before this direction is buildable.

**Source:** user, session 2026-07-21.
</content>
