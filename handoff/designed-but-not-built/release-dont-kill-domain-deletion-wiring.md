# Release-don't-kill domain deletion — DESIGNED, not built

**What:** `delete_domain()` should delete the domain's memory entries AND release its expert affiliations (stop routing
traffic), then let the existing culling mechanism naturally remove any expert left with zero constituency — WITHOUT ever
touching expert parameters directly.
**Status:** semantics agreed with the user (see `../decisions/domain-deletion-RELEASES-experts...`). The wiring is not
implemented. A small, well-defined build.
**Source:** context export §11, Phase 7.
