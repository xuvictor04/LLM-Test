# Corroboration-based wrongness detection (B redesign) — PROPOSED, not built

**What:** the only plausible fix for B's ~1% precision: instead of "is this token surprising?", ask "does this entry
DISAGREE with its nearest neighbors in the store, given enough neighbor evidence to judge?"
**Status:** proposed, never built. Real risk it still fails — but it would fail for a different, informative reason rather
than repeating the known-broken surprise≡wrongness signal.
**Gated by:** `../open-questions/Q3-B-direction-attempt-corroboration-or-cut-B-and-ship-A.md` (prior-context rec is to CUT B instead).
**Source:** context export §5 (B), §11.
