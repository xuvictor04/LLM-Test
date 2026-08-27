# Phase 9 — the goal check: "it needs to produce language and be intelligible"

The user stated language quality is the actual point, and asked whether dropout / augmentation / weight-decay should be
added as a matter of course. Claude checked rather than assumed: more passes over the same corpus monotonically improved
the model with no plateau, and a per-run LM loss curve confirmed it was still falling steeply at the end. **The model was
severely UNDERFIT, not overfit** — regularization would make language quality worse. Declined dropout/decay as defaults,
built them in but OFF, and added a proper validation split + train-vs-held-out **memorization check** with a decision rule.

Same investigation surfaced a key number: the product loop's active corpus was only **~5.7MB unique**, sampled with
replacement so only ~65% (~3.7MB) was ever seen — thousands× less than a small production LM. **Fluent language was never
a realistic outcome at that scale, independent of any architectural choice.**
</content>
