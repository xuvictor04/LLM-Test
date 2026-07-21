# Phase 5 — the flat expert bank: built, measured negative, diagnosed

The user proposed "expanding experts and a router fabric" on a "society" model. Claude's FIRST build tied one expert to
each domain 1:1 with hard top-1 routing — explicitly the wrong design (corrected in Phase 6), but a useful NEGATIVE
result: hard-routed per-fine-domain experts HURT performance (negative bits/byte) even after fixing real bugs along the
way — overly-strong culling killing experts before they specialize (fixed with a grace period, then rank/capacity-gated
selection), and a train/eval routing mismatch (measured with a pinned-vs-routed diagnostic). Even fixed, the flat 1:1
bank never became net-positive. This + the user's memory of a prior fabric already in `legacy/system.py` → the Phase 6 pivot.
</content>
