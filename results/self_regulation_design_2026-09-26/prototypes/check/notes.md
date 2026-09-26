# Check of rev/04_SELF_REGULATION.md (independent checker)
- rev/metrics.py rerun (OMP_NUM_THREADS=1, cwd scratchpad) -> byte-identical to rev/metrics.txt (check/metrics_rerun.txt).
- Spot checks: chk1.py (d2 tags), chk2.py (graft, act6, d1, sel, walls, counters), oracle pairing, td_* stress, mf, repro.
- Majors: REPLAY_NEWEST 1.7 != critic replay_late (needs 2.33); seg_log "rng" key collision with _replay_segmentation;
  entry-point count misses typed period accessors, focus constructor, stream_state/restore moves; ~44 new levers
  unaccounted, DATA_SYNTH_KIND not in tree, DATA_REHEARSE_PARENT missing; EVAL_RETENTION_EVERY derived from DATA_DRAW
  is a wire (0 wires claimed); synthetic holdout admission ignores offset/key and a "reason" that is not recorded;
  holdout_probe producers (units_by_domain, logits_fn) unnamed; probe at 1000 windows never fires on default 120 KB run.

# Re-check (checker round)
- All 8 majors and 14 minors fixed in text; counts verified against tree (levers 18/17/12/13, 262+44=306; 141+11=152; 7 moves; DEFERRED 23).
- New: E1 rule 1 flips DATA_DRAW only, while EVAL_RETENTION_EVERY stays 1000 (arms tested at 160) -> untested default.
- New/pre-existing: DATA.redraw_tail and _replay_segmentation lack `seed` (rng_for needs it; Plan/Areas carry none).
- Minor: _holdout_tokenize must pass view=view_of(vocab) (else writes _retok_cache, counts tok.segment);
  REHEARSE_PARENT conditional in §5/§6 vs unconditional in Q4; E1 arm "retention at defaults" vs "arms set 160";
  FocusPlan/Reading record types not counted; checklist m6 row stale (+1 move, n_windows).
